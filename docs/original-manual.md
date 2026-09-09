# Original MATLAB manual

Historical documentation extracted from the original DOCX. Instructions
and runtime claims describe MATLAB, not the current Python implementation.
See [the concise guide](legacy-workflows.md) for the workflow summary.

Cortico-cortical evoked potentials graphical user interface program user manual

Hello, and thank you for downloading this program. I would like to clearly state that this program should be used for research only, and no clinical decisions should be made based on the results of it. This program was designed to help researchers and clinicians working with Stereoelectroencephalography (SEEG) data to better organise and view the results of their Single Pulse Electrical Stimulation (SPES) and CCEP data. The overall goal of this program is to streamline the process to generate large-scale anatomical connectivity analyses in SEEG patients. In this manual, the most important steps will be described, with pictures to aid in parts where there are difficult to describe interactive elements. 

Organising your data:

Setting up the CCEP toolbox files:

To run the CCEP toolbox code, you will simply need to unzip the CCEPGUI.zip folder, and place the “CCEP Toolbox” folder anywhere on your computer. After this, open Matlab and add the “CCEP Toolbox” folder to the path. Calling “CCEPGUIInit” from the command line will add all downstream folders and open then main menu for the first run.

MRI, CT and EDF Files

When copying your data into files, I would recommend that you separate each patient’s information into an MRI, CT and EDF folder. For organisation’s sake, I would also recommend including the patient’s name at the start of each file. For example, calling the Nifti MRI image: “PatientName MRI.nii”, and the CT image “PatientName CT.nii” would help keep track as more patient’s are added to your studies. We also took to calling the .edf files “PatientName CCEP 1.edf” and so forth. This will also help the automatic identification of files in the CCEP program (and ultimately less painstaking folder searches, looking for the electrode files).

Using the CCEP-GUI program

Viewing the recommended stimulation parameters

To view check the stimulation settings which you are utilising for safety, use this button from the main menu. This will open a figure which displays an axes of Stimulation Current (y-axis) vs Pulse width (x-axis). Enter your electrode geometry and the size of the electrode contacts, then input your electrical stimulation settings. You can also compare your parameters with other studies, and can also view the details of these studies, either by opening the “CCEP Studies Supplementary Tables and Papers” spreadsheet, or clicking the “Show table of selected studies” which will open a separate figure with descriptions of all parameters. Please note that the charge limits described in Gordon et al. (1990) were defined by stimulation at 50Hz (roughly 20mins continuous stimulation, spread out over several hours). In our opinion, the cortical damage caused by electrical stimulation using CCEPs and Single Pulse Electrical Stimulation will be far less than that caused by 50Hz stimulation.

Adding files and folders to the path

Use this feature to quickly select folders to add to the Matlab search path. This is effectively the folders that the program be able to access to find files and functions. Your data folders would be important folders to add. You may have to add these folders upon Matlab start-up each time you run this, depending on your configuration of Matlab preferences. 

Imaging pipelines:

All imaging pipelines were designed and tested on Windows 7 and 10 64-bit versions. The image processing relies on the Statistical Parametric Modelling 12 toolbox (SPM12). Please note that all images viewed in SPM12 are displayed in Neurological format, that is, Left is on the left and right is on the right in SPM12’s display system. 

Running the imaging steps:

Please note: The program was developed to use MRI-CT coregistration, but can also be used with a Pre-Implantation MRI and a Post-Op MRI (with electrodes inserted). To use a post-op MRI, just use the post-op MRI as the CT scan. This will be fine, since all electrode points are acquired manually, using the CoOrdAcquire GUI. 

Before beginning the imaging steps, you will need three files:

The T1 structural MRI.(MPRAGE2 recommended)

The bone-window CT. (preferably SEMAR) 

The completed excel spreadsheet anatomical map.

If the MRI or CT files are still in DICOM format, please use SPM12’s “Dicom Import” feature, or MRIConvert (https://lcni.uoregon.edu/downloads/mriconvert) to convert the dicom images to Nifti (.nii) files. 

It is also important to check that the electrode names are correct in the excel spreadsheet. If there is a problem with the Electrode names, then there could be problems later in the processing. I would also highly recommend, keeping a copy of your original anatomical map spreadsheet, as well as a formatted version which contains the standardised anatomical names and labels (In a sheet labelled “Formatted”). 

Once you have the MRI and CT in .nii format, and you have renamed and created a formatted copy of the anatomical labels in which the MRI was implanted, add the folders to the Matlab path using the “Add files and folders” tool, from the main menu.

Preprocessing the MRI and CT

Then click “Preprocess and MRI and CT” in the main menu. Enter the name of the patient you are inputting (remember, this should be the same as the map spreadsheet title).

The next step is to select the MRI file that you would like to use. Browse to the MRI (.nii) file that you would like to coregister the electrodes to (pre-operative structural MRI). The program will then ask you to select the CT image containing the electrodes. If you are using a post-op MRI (with electrodes implanted), then select this in place of the CT image. 

Once the MRI and CT files are selected, the next operation is to align the origins of both scans to the anterior commissure. 

Tips for manual rotational re-alignment and origin selection

When performing a rotation alignment in either CT or MRI, set the centre of the head as the origin, since all rotational transforms occur about the origin point. Then apply corrections in the angles of all 3 pivot axes. Respectively, Yaw corresponds to Axial/Transverse. Roll will pivot the Coronal image. Lastly, pitch will act on the Sagittal plane. The angles for yaw, roll and pitch are input in radians (Pi (π) = 1800). You will need to reset the anterior commissure as the origin before you “Reorient” the scan.

Set the origin and perform the rotation first for the MRI, and once the new origin is selected; then click “Reorient” in the SPM12 graphics figure. Then overwrite the image without saving a reorientation matrix. After the MRI figure redisplays, click the “ok” button in the small figure that appeared when the MRI first opened. The image that you selected to be the CT scan will then appear, accompanied by another small placeholder figure. Set the origin to the approximate location of the anterior commissure, and get the CT image roughly into alignment with the MRI image that you processed previously. Once you are happy with the scan alignment (including rotation), click “Reorient” to save it, and then click the small figure window to begin processing the scans. Once you have done this, the processing will take at least 40mins to perform the segmentation and coregistration, so go have a coffee (or 2). Once there is an output figure from the Computational Anatomy Toolbox (CAT12 toolbox), assessing the quality of the MRI, there will be 

Acquire electrode positions and create electrode file

After the MRI and CT have finished their alignment and preprocessing, next you will need to manually acquire the electrode Co-Ordinates (CoOrds). We have developed a GUI which has been designed for SEEG (depth) electrodes. To initiate this process, click the “Acquire electrode positions and create electrode file” button in the Main GUI. After you initiate this, you will need to select several files in this order, when prompted:

The CT (or post-op MRI) image in register with the structural MRI. This should have the prefix “RealignedCoreg” before the original CT file name.

The imaging information data structure.

The original MRI file.

The deformation field of the MRI file.

You will first be asked what the patient’s name is, type this into the input window and click “Ok”. The patient’s name should be exactly as it was spelled in the electrode map spreadsheet filename (case sensitive is a good idea).

After this, select the CT file, which is in alignment with the structural MRI, as described in point 1.

Then obtain the imaging information as described in point 2. This file should be labelled “PatientName Imaging information.mat”. 

After the imaging information, you will need to select the original MRI file. This will be the file that you selected at the beginning of the preprocessing steps.

Finally, you will be asked to select the deformation field for the MRI file. This contains the local voxelwise translations used to convert the patient space CoOrds (Pat-CoOrds) into MNI space (MNI-CoOrds). Effectively this will be used as a method to translate the SEEG CoOrds you select into ones that can be used in a standard space. This is based on the MNI-152 atlas. The MNI-CoOrds will be used to look up the template labels.

Acquiring the CoOrds

The CoOrd acquisition figure should pop up in the top right of your screen. This is automatically populated by the anatomical map spreadsheet. If there are errors with the electrode names, the way to fix them is by changing their names in the “Formatted” sheet of the electrodes. Please make sure that you have the electrode names (without any numbers in them, unless they have numbers in the names in your centre). Remember that in SPM12, left is left, and right is right.

If all of the electrode names are ok, then you can start to alter the number of contacts on each electrode by using the dropdown menus on each of the electrodes. The default number of contacts is 15 (which we found to be the most commonly used size), but we have made the option available to use between 3 and 20 contacts. When you are selecting this, select the amount of contacts on the electrode used, not the amount of contacts in the brain. The electrodes outside of the brain (as labelled in you map spreadsheet, will be removed upon import of your .edf data files). 

To acquire the electrodes you will need to use the SPM12 cross hairs to select the most mesial (start) CoOrd of the electrode you are gathering data for. The zoom dropdown menu on the SPM12 figure window (which is originally labelled “full volume”) is useful to capture the location exactly. We have found that 80mm was a useful zoom ratio to use. The zoom will re-centre around the current crosshair point, so it can be useful to move the image data viewed  by reselecting the frame size that you want. Once you are happy that you have the cursor over the centre of the most mesial electrode contact, then click the “ElectrodeName Start” button (making sure you have the correct number of contacts for the electrode). Once the button turns green, the start has ben acquired. You will then need to move your cursor to the most lateral contact of the same electrode and then click the “ElectrodeName End” button. This will fill out the electrode data and input it into the structure. If you want to reacquire the start and end, this can be done, in the same process, but you will need to click both the electrode start and end buttons in series again in order for the data to be overwritten (the electrode interpolation is performed on acquiring the “End” CoOrd of each electrode. Do this for all electrodes to acquire them one-by-one.

Once you have acquired all of the electrode CoOrds, you can show your results in patient-space by clicking the “Plot Electrodes” button. Only do this once you have acquired all electrodes, otherwise the program will throw an error. If after seeing your electrodes plotted you are happy with the results, you can click the “Process MNI CoOrds and ROIs” button, which will automatically acquire the MNI positions and get the tissue types for the images. This will probably take about an hour, so it might be a good time to go caffeinate and rest your eyes.

Viewing electrodes

Once the electrode structure file has finished processing, you will then be able to view it and check that it has accurately captured the information you acquired. Pay close attention to the labels which are displayed in this, if you are happy with the results, then you are finished with the imaging section of the processing.

SEEG data processing

Viewing the data and adding/altering annotations and stimulation pulses

Now that you have preprocessed the images and acquired the SEEG CoOrds, you will then be able to open up a .edf file to view the SEEG data recorded. The CCEPSEEGViewer can work for any .edf that you have completed an anatomical map and processed electrodes structure for, not just files containing CCEP or cortical stimulation. 

To view a file, click the “View SEEG files and alter annotations” button. Then enter the patient’s name as it appears on the corresponding anatomical map spreadsheet and the electrode file. Then select the .edf file as the file to view. 

SEEG Viewer:

To use the viewer, an image is shown below identifying its most useful interactive elements:

![Original MATLAB workflow](assets/manual/image1.PNG)

Figure 1: SEEG Viewer figure used to check .edf files and look through the raw data. This can also be used to add or change annotations and to add stimulation pulse times as well

The SEEG viewer is shown above in Figure 1, most features are obvious, we will describe the more obvious features of the viewer, and then move to ones which are less common in clinical SEEG analysis. There are four drop down menu’s.

Time span (amount of time shown on a page)

Voltage gain (which can increase the sensitivity without changing the offsets of channels)

Referencing (which can be swapped between unipolar (recording ground referenced) or adjacent contact bipolar)

Annotations list, which will snap to the time of an annotation, putting it in the centre of the page. 

The left-hand side contains the list of electrode channels currently available for display. These labels will depend on the type of referencing being used. The ones selected are shown in blue/gray. Select multiple channels at once to import many channels simultaneously. Each time a new channel is selected, then the SEEGEDFImport routine will load those channels from the .edf file selected. The slider at the bottom of the figure is used to scroll through the data which is used. The slider’s step is also dependent on the Time Span selected. There are also dotted grey lines on the axes to denote 1s increments, as in clinical SEEG viewers.

As shown in Figure 1, the annotations times are shown in red, and the stim pulse times are shown in black lines. These pulse times are automatically acquired from the default channel that is selected as the “DefaultStimLabel” parameter in the initialisation function. If no synchronous trigger channel was used, then you will be able to manually select pulse, which is described below.

Several of the less obvious features are labelled in Figure 1, indicated by the boxes in red labelled with numbers 1-3. 

Is a toggle button for whether to show filtered or raw data. By clicking it, you can change turn filtering on or off. If SEEG data is displayed when this is pressed, then all data will be filtered and shown again (this could take a little while if you have many channels open).

Shows two push buttons which are used to acquire or remove stim pulse markers. Clicking the “Mark pulse time” button will initiate a cursor on axes, which you can then use to mark the time when a single stimulation pulse occurs. The “Remove last pulse” button is used to remove the last manually acquired pulse (pretty sensible name, don’t you think?). It will not however remove any automatically acquired pulses (from a trigger channel).

The “Annotation Editor” in the top right opens the annotation editor figure, which can be used to add annotations and save an annotations file (along with manually marked stim pulses times) that are acquired. A description of this is shown in the next section.

These are the main elements of the SEEG Viewer, the following section will describe the annotation editor, which works alongside the SEEG Viewer figure. I would also like to state that Matthew Woolfe, a fellow PhD, worked to develop the vast majority of the EDF reading and SEEG viewing functionality as part of his PhD output.

Processing an RMS file:

Once you have adjusted the annotations and viewed the SEEG data (as well as previously acquiring the electrode locations), you may then process the .edf file into an RMS results file. The finished RMS results file will be labelled “EDFFileName RMS Values.mat” and will be located in the same folder as the .edf data file. 

Compiling and viewing the aggregate results

Adding a processed RMS file to the CCEP repository:

Once you have output a processed RMS results file, you will then be able to add it to the CCEPRepository (CCEPRepos). You can use the “Add file to CCEP repository” to create a repository, and then add subsequent files to it. You will need to add RMS results files to the repository one by one. Make sure that the repository files are on the CCEPGUI path, or else an error will occur. This is to make sure that no unintended files are added to the repository. Please make sure that you add only files that you desire to the repository, once added, the results cannot be removed. The only way to remove results is to delete the “CurrentCCEPRepository.mat” file, and then create a new one. 

Viewing the RMS and ERP results:

Once all of the files that you would like to add to the CCEPRepos have been added, you can then open the Repository search tool. This will allow you to search by stimulation location as well as the anatomical sites present in the implantations, and the stimulation levels a stimulation frequencies employed in the physical stimulation. A brief of the outputs and key interactions is shown below:

![Original MATLAB workflow](assets/manual/image2.png)

Figure 3: The repository viewing GUI. Use this to sort through the results added to the CCEP repository. Many other results viewing functions can be accessed from this figure

The repository viewer, shown in Figure 3 is used to sort through results and can be used to perform the majority of results analysis and can also create connectivity studies of the selected stimulated areas. 

The listboxes (shown containing the blue highlighted text) are used to narrow the search. Any change made to the selections on any of the lists will update the table which is shown on the right (labelled number 3). This will also update the number of unique patients and unique stimulation sites (labelled number 1). 

The push buttons (labelled number 2) are used to view the electrode data, the location of stim sites, perform anatomical connectivity studies and to view the ERPs and the resultant connectivity ranks for different files. These will be described briefly below:

Plotting electrode information for stimulation sites and implantations

The “Plot Electrodes” and “Plot Stim Sites” buttons do very similar tasks, both of these buttons allow the electrode CoOrds to be plotted on top of a patient-space brain to provide a quick visual inspection of where stimulation locations and implanted electrodes are in the subset of selected patients. A figure highlighting the interactions are shown below:

![Original MATLAB workflow](assets/manual/image3.png)

Figure 4: The electrode and stim site viewing figure which displays the electrode information of the selected parameters in the repository viewer. The items in red allow you to jump between showing all electrodes for specific patients, and only the selected stim sites (for all patients in the repository viewer).

Once the figure displaying the selected patients electrodes or stim sites appears, you can use the listbox and buttons on the right to change the CoOrd space (for both the stim site locations and all electrodes implanted). The “Reset” button will revert to showing only the stimulation sites. Selecting one or more patients from the listbox in the top left will plot those patient’s electrodes implantations on the brain surface.

Creating an anatomical connectivity study

The primary use of this toolbox is to allow the streamlining and simplification of anatomical connectivity analyses. This can be accomplished by selecting which stim sites and connections you would like to analyse in the repository viewer (Figure 3), and then clicking the “Connectivity Analysis” button. In the connectivity studies, white matter, out and any labels included in the “BadAnatomicalLabels” parameter of the initialisation routine will not be ranked in the connectivity analysis, so that they do not skew the results if they are included.

![Original MATLAB workflow](assets/manual/image4.PNG)

Figure 5: An output spreadsheet from the connectivity analysis of many anatomical sites. The results are sorted by the average rank value (which is normalised for each patient respectively, and then tabulated). Each sheet contains the result for a different anatomical site analysed.

View ERPs and Rank results for individual files

In order to determine the connectivity of specific anatomical sites in individual patients, the “View ERPs & Ranks” button will open a GUI which acts on the selected anatomical sites in the repository viewer. This allows up to 12 channels to be plotted, and then ranks may be called. An example of the figure with ERPs displayed, and the corresponding ranks are shown below:

![Original MATLAB workflow](assets/manual/image5.PNG)

Figure 6: The ERP viewer showing 6 channels (3 of the left Amygdala, 3 of the right amygdala). This is in response to the stimulation in the pulse train selected in the listbox on the right. The channels to plot are selected as well in the listbox on the right, with up to 12 being displayed due to the decreasing size of the plots as number of axes increases.

The ERPs from channels plotted in Figure 6 can also be ranked, by clicking the “Create Ranking Table” button, which will then open the ranked results for the aggregate of all pulse trains selected (only 1 in this case). The channels shown in the plots are also highlighted in yellow.

![Original MATLAB workflow](assets/manual/image6.PNG)

Figure 7: Ranking results table for selected stimulation sites, those highlighted in yellow include the channels shown on the ERP viewer (Figure 6). 

The data can be re-ranked by clicking the “Sort ranking data” button, if you alter which pulse trains are selected from the listbox, or you select different channels to be plotted in the ERP Viewer. 

Final remarks:

That concludes the description of how to use the GUI. If you are interested in the methods or looking for more information on Cortico-Cortical Evoked Potential Processing I would recommend you look at my thesis: “Evaluating, improving and applying Cortico-Cortical Evoked Potentials in Stereoelectroencephalography” (David Prime, Griffith University). 

Best of luck in your research.
